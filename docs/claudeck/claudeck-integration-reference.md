# Claudeck Integration Reference

**Last updated: 2026-07-23** · claudeck v1.4.2 (MIT, github.com/hamedafarag/claudeck) · npx-installed, server on `localhost:9009`, data in `~/.claudeck/`

Claudeck is the operator cockpit for Claude Code sessions across all `/opt` projects.
It is a **replaceable cockpit, never a dependency**: all changes below live either in
this repo (permanent) or in claudeck's npx cache (wiped on update, re-applied daily
by the patcher). The spine — docs, shims, enforcement, CLI, git — works without it.

## Update-survival model (read this first)

| Layer | Survives claudeck update? | Mechanism |
|---|---|---|
| Fabrik scripts (importer / patcher / repair / backfill) | **Yes** | in git |
| npx-cache patches (model menu, aliases, system CLI, detach) | **Wiped, then re-applied** | `claudeck_patch_fable.py` runs daily via `wsl_startup_hook.sh`; run manually for instant re-patch after an update |
| Claudeck data (`~/.claudeck/data.db`: sessions, titles, pins, backfilled transcripts, memories) | **Yes** | user data; updates don't touch it |
| Session curation (which chats are listed) | **Yes** | `CURATED` map in the importer re-enforces on every run |
| Desktop shortcut, startup-hook wiring, `settings.json` model default | **Yes** | outside claudeck entirely |

Patcher caveat: patches use exact text anchors. If a future claudeck version
restructures the patched files, the patcher **no-ops silently** — after any update,
run `python3 scripts/claudeck_patch_fable.py` and check its output lines.

## 1. Detach patch — runs survive hibernation / tab close / disconnects (`9102783b`)

**Problem.** Stock claudeck ties run lifetime to the WebSocket: `handleClose` aborts
all active SDK streams and the stream loops `break` on `readyState !== 1`. Closing a
tab, refreshing mid-run, or hibernating the machine killed in-flight work.

**Change** (in `server/ws-handler.js`, both npx installs, patcher section 4):
- `handleClose`'s abort loop dead-coded (`if (false)`) — disconnect no longer aborts.
- Chat stream loop keeps consuming SDK events when the socket is gone; results
  persist to the DB; sends are already readyState-guarded so nothing throws.
- Workflow loop: kept `wfAborted` semantics, dropped only the disconnect-break.
- Explicit **Stop** still aborts (separate message path, untouched).

**Effect.** Hibernate/sleep/close mid-run → run continues server-side → reopen the
chat and read the result. Arms on server restart after patching.

**Trade-off.** A run blocked on a permission prompt while detached receives an
auto-deny ("WebSocket disconnected") — use Bypass mode for autonomous runs.

## 2. Session adoption: list, titles, ordering, history (`d0c11db1`, `a38be6a0`, `09a6f154`, `6b39f6fe`…`bce42e8e`, `3a4793f4`)

Claudeck lists/renders **only its own SQLite** — it never reads `~/.claude/projects`
(verified: zero references in its source). Adopted chats therefore needed:

- **`scripts/claudeck_import_sessions.py`** (daily via startup hook): adopts native
  sessions into claudeck's DB using its own `createSession` insert shape; `id` = the
  Claude session uuid (idempotent). Fixes learned the hard way: timestamps in
  **epoch seconds** not ms (year-58525 bug); `last_used_at` read from the **file
  tail** (head-capped scan sank long operator chats to the list bottom); grouping by
  **top-level `/opt` entry** (fabrik-lib modules, worktrees, subdir cwds fold into
  the parent — a fabrik-lib module is never a project); automation excludes
  (`kilo-benchmarks`, `iterative_image_editor`; `--include-all` overrides).
- **`CURATED` map** (in the importer): per-project allowlists — only named session
  ids are listed for youtube (2), fabrik (3), fabrik-lib (3), trade-intelligence (2),
  brand-identiy-creator (1). Deletes are **list rows only**; native jsonl untouched;
  fully reversible by removing the map entry and re-running.
- **Titles**: the VS Code extension's display titles live only in its private
  storage (verified unreachable: not in WSL vscode-server nor Windows globalStorage)
  — titles are hand-set from operator input or derived from the first user message.
- **`scripts/claudeck_backfill_messages.py`**: rebuilds the transcript pane from the
  native jsonl as readable prose (user + assistant text; tool noise, thinking and
  neutralized markers omitted). Full delete+reinsert per session because the UI
  renders `ORDER BY id`. Claudeck loads whole transcripts unpaginated — very large
  panes (18k msgs) may render slowly; backfill can be capped if needed.
- **Detection of open extension chats**: live `claude --resume=<id>` processes
  enumerate what's open in VS Code (`ps` scan) — used to auto-discover the six
  chats worth adopting.

## 3. Model menu: real models, no traps (`14fd8d95`, `90923adb`, `eb343721`)

- **Fable 5** added to the GUI (header Session ▾ → Model + hidden select + meta-bar
  label) as explicit `claude-fable-5[1m]` — the server's `resolveModel` passes
  unknown ids through verbatim, so no server change was needed for it.
- **Opus 4.8 / Sonnet 5 / Haiku (latest)** send **family aliases** (`opus`,
  `sonnet`, `haiku`) which the CLI resolves server-side to each family's latest —
  permanent parity with the VS Code extension, zero version chasing. All entries
  live-probed. The stock map's hardcoded `claude-opus-4-6` caused instant exit-1
  spawns (the "Connecting to Claude…" hang).
- **No baked-in default**: selection is the operator's click, persisted by the
  browser in localStorage (`claudeck-model` key) — it survives restarts by design.
- **Auto** = no override = the CLI default from `~/.claude/settings.json`
  (currently `claude-fable-5[1m]`, operator-owned).

## 4. System CLI wiring (patcher section 3)

Claudeck's SDK bundles Claude Code **1.0.128** (~1 year old): no plugins, no
skills, stale tool set. Consequence: adopted 2.x sessions 400'd on replay ("Tool
reference 'Monitor' not found") and episodic-memory/`/fab-*` skills never loaded.
Patch injects `pathToClaudeCodeExecutable` → the **system CLI's `cli-wrapper.cjs`**
(resolved dynamically from `which claude`; currently 2.1.218). Every claudeck chat
now runs the same CLI as the terminal: plugins, skills, current tools.

## 5. Session repair: extension-only tool landmines (`10e67b8d`)

VS-Code-extension sessions contain tool_use blocks for **extension-context tools**
(`Monitor`, `Agent`, `ScheduleWakeup`, `TaskOutput`, `TaskStop`, `ToolSearch`,
`Workflow`, `Artifact`, `ReportFindings`, `SendMessage`) that don't exist headless.
The API validates **all replayed history** against current tools → hard 400 on
resume. **`scripts/claudeck_session_repair.py`**: whitelist-based (CLI-native names
+ `mcp__`/`plugin__` prefixes pass; everything else → inert text blocks, paired
tool_results too), strips stored "API Error:" assistant messages (they re-render
forever and claudeck's auto-memory re-captures them into prompts — purge
`memories`/`messages` rows when that happens). `--dry-run` supported; timestamped
backups. Run on every adopted session **before first resume**. ~2,600 blocks
neutralized across the nine adopted chats.

## 6. Operations

- **Backend always-on**: startup hook starts claudeck if `:9009` isn't listening
  (`1d5a3406`). Manual restart: kill the pid on 9009, `nohup npx -y claudeck`.
- **Desktop shortcut**: `Claudeck.lnk` → `brave.exe --app=http://localhost:9009`
  (PWA-style window). Requires the WSL backend up (hence always-on).
- **Two npx installs exist** (`42d3…`, `b861…`); launches may resolve either — the
  patcher patches **all** of them.
- **Parallel Mode** = 4 lanes of ONE session (per-session fan-out), not
  multi-session tiling. Multi-project = browser tabs/windows (cross-tab sync is
  native); each tab's close aborts only ITS runs — moot after the detach patch.
- **Adoption kit per project**: detect open chats (`ps` scan) → `claudeck_session_repair.py`
  → curate (`CURATED` + delete rows) → titles → `claudeck_backfill_messages.py` → re-import proof.
- **First message on an adopted session** pays full MCP cold boot (30–120s) —
  "Connecting to Claude…" with a live young `claude` process is healthy; the same
  UI with an instant-exit process was the bug (now fixed).

## 7. Known limitations / upstream candidates (hamedafarag/claudeck)

1. Spawn failures swallowed behind eternal "Connecting to Claude…" (no error surfaced).
2. Hardcoded stale model map (shipped `claude-opus-4-6`).
3. Year-old bundled SDK/CLI (1.0.128).
4. Run lifetime tied to connection (fixed locally by detach patch — PR candidate).
5. Transcript pane unpaginated; adopted sessions render empty without backfill.
6. Auto-memory captures API error text and re-injects it into prompts.
