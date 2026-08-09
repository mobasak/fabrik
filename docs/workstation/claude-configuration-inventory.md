# Claude Configuration Inventory (this WSL box)

Every file and directory that configures or is written by Claude on this workstation — what each one
does and its state today. Verified by live probe 2026-08-03.

**Headline:** `~/.claude` is **9.7 GB** (98% of it session data, not config), plus a **2.0 GB** second
headless profile and a **3.4 GB** node cache. Two CLI surfaces (WSL + Windows) and Claude Desktop each
carry their own MCP roster.

---

## 1. Primary CLI config (WSL)

| Path | Function | State |
|---|---|---|
| `~/.claude.json` (82 KB) | Main config — MCP server definitions, per-project registry, model prefs | **Live**, rewritten continuously |
| `~/.claude/.credentials.json` (509 B, `600`) | OAuth tokens for the active account | **Live** |
| `~/.claude/settings.json` (2.6 KB) | User settings: `env` · `permissions` · `model` · `hooks` · `statusLine` · `enabledPlugins` · `extraKnownMarketplaces` · `effortLevel` · `tui` · `voice` · `skipDangerousModePermissionPrompt` · `theme` · `agentPushNotifEnabled` · `voiceEnabled` | **Live** |
| `~/.claude.json.backup`, `.backup.20260603-214445`, `.bak-20260725`, `.tmp.*` (2) | Auto-written backups / interrupted atomic writes | Stale — safe to prune |
| `~/.claude/settings.json.bak*` (5: `.bak`, `.bak2`, `.bak3`, `.bak-fable`, `.bak-thinking`) | Manual snapshots from past settings edits | Stale |

### Authored config (the parts you maintain)

| Path | Function | State |
|---|---|---|
| `~/.claude/agents/` (24 KB) | 4 custom subagent definitions: `design-review`, `fabrik-gui`, `fabrik-researcher`, `fabrik-reviewer` | **Live** — dispatched by the `/fabrik-*` commands |
| `~/.claude/commands/` (452 KB) | 18 rendered slash commands (`/fabrik-*` + `/design-review`) | **Live** — generated from `/opt/fabrik/commands/_sources/` by `assemble_commands.py`; never hand-edit |
| `~/.claude/skills/` (60 MB) | 57 skills — the 18 command twins plus `fab-ettw-*` / `fab-mega-*` orchestrator steps and third-party skill packs | **Live** |
| `~/.claude/plugins/` (163 MB) | Plugin + marketplace state: `known_marketplaces.json`, `installed_plugins.json`, `blocklist.json`, and 4 cloned marketplaces (`anthropic-agent-skills`, `claude-plugins-official`, `superpowers-marketplace`, `claude-code-skills`) | **Live** |
| `~/.claude/commands-backup-20260721-*.tgz` (2 × 126 KB), `commands.bak-20260721-0615/` | Pre-render snapshots taken by `assemble_commands.py --extract` | Frozen baseline — `--extract` re-reads the `.bak` dir, so **do not delete** while that mode exists |

### Session & runtime state (the 9.7 GB)

| Path | Size | Function | State |
|---|---|---|---|
| `~/.claude/projects/` | **6.9 GB** | Per-project session transcripts (`.jsonl`) — the corpus `session-recall` indexes | Live; largest item on the box |
| `~/.claude/file-history/` | **2.2 GB** | Edit undo history per session | Live; never pruned automatically |
| `~/.claude/session-env/` | 186 MB (46,789 entries) | Ephemeral per-session env dirs | Live; entry count is the real cost, not bytes |
| `~/.claude/telemetry/` | 141 MB | Anthropic usage telemetry queue | Live |
| `~/.claude/sessions/` · `todos/` · `tasks/` · `shell-snapshots/` | 1.4 MB / 92 KB / 12 KB / 464 KB | Session index, todo lists, background-task registry, shell state | Live |
| `~/.claude/history.jsonl` | 656 KB | Prompt history | Live |
| `~/.claude/statsig/` · `cache/` · `paste-cache/` · `debug/` · `downloads/` | ≤476 KB each | Feature flags, changelog cache, paste buffers, debug dumps | Live, low cost |
| `~/.claude/sound-debug.log` | 316 KB | Debug log from the notification-sound hook | Growing; prune candidate |
| `~/.claude/mcp-needs-auth-cache.json`, `stats-cache.json`, `.last-cleanup`, `.last-update-result.json` | small | MCP auth prompts, usage stats, cleanup + self-update markers | Live |
| `~/.claude/bin/` (`claude-sound.sh` + `claude-stop-decider.py`) | 36 KB | Notification-sound hook router + the state-based stop decider (rings only at true final rest) | **Live** — DR-mirrored via `dr_claude_backup.sh` |
| `~/.claude/ide/*.lock` | 36 KB | VS Code extension ↔ CLI handshake locks | Live |
| `~/.claude/chrome/chrome-native-host` | 8 KB | Chrome native-messaging host | Present |

### Account rotation

| Path | Function | State |
|---|---|---|
| `~/.claude/.claude-manager/` (60 KB) | Rotation engine: `active-sessions.json`, `usage-history.json` (31 KB), `session-start-tap.js`, `statusline-tap.js`, `statusline.json` | **Live** — drives the quota rotation |
| `~/.claude/manager-accounts/` (288 KB) | Credential snapshots for the 3 accounts: `ob-`, `mob-`, `can-ocoron-com-s-organization` | **Live** |
| `~/.claude/.claude-manager-snapshots/`, `~/.claude/backups/manager-accounts.backup.20260710-222349` | Historical account snapshots | Retained |

---

## 2. The CLI binary and caches

| Path | Size | Function | State |
|---|---|---|---|
| `~/.local/bin/claude` | symlink | Entry point → `~/.local/share/claude/versions/2.1.219` | **Live** — v2.1.219 |
| `~/.local/share/claude/versions/` | 523 MB | Installed versions `2.1.218`, `2.1.219`, `2.1.220` | 2 older versions are prune candidates |
| `~/.cache/claude-cli-nodejs/` | **3.4 GB** | Node/npm cache for CLI + MCP subprocesses | **Largest cache on the box** — reclaimable |
| `~/.cache/claude/` · `~/.cache/claude-fleet-sync.log` | 8 KB / 4 KB | Changelog cache; fleet credential-sync log | Live |
| `~/.bashrc:188` | — | `alias mmc-claude='consult "opus,sonnet,haiku"'` | Live |

---

## 3. Second CLI profile — youtube headless ⚠️ ACTIVE

`~/.claude-youtube-headless/` (**2.0 GB**) is a **complete separate Claude profile**, not residue.

- Selected via `CLAUDE_CONFIG_DIR=$HOME/.claude-youtube-headless`
- **Driven by two crontab entries**: `@reboot … rag_backfill_supervisor.sh` (the RAG backfill supervisor,
  `RAG_SUP_CONCURRENCY=5`) and a daily 05:17 prune of its `projects/` older than 1 day
- Consumed by `/opt/youtube/scripts/{start_all.sh,rag_backfill_supervisor.sh}`
- Mirrors the main profile: `.claude.json` (39 KB), `.credentials.json`, `settings.json`, `plugins/`,
  `projects/`, `sessions/`, `telemetry/`, `file-history/`, `shell-snapshots/`, `backups/`, and its own
  **43,919-entry `session-env/`**

**Do not delete or clean this profile without stopping the youtube RAG pipeline first.**

---

## 4. Traycer host ⚠️ ACTIVE (regenerated daily)

`~/.traycer/` is live infrastructure despite the Traycer *workflow* being retired:

- **Two enabled + running systemd user units**: `ai.traycer.host.service`, `traycer-pid-sync.path`
- `~/.traycer/cli-agents/` is **regenerated every day at 06:00** by
  `/opt/fabrik/scripts/kilo-benchmarks/daily_refresh.sh` → `generate_kilo_agents.py`, with dated
  backups (`cli-agents.backup.YYYYMMDD-060041`)
- Also holds `mcp.json`, `routing-policy.yaml`, `prompt-templates/`, `epics/`, `worktrees/`, `snapshots/`
- `~/.traycer/.claude/skills/` is a **stale mirror** of the fab-ettw skills, frozen 2026-07-22

> **Open question for the operator:** the daily pipeline still generates **Kilo** agent shims into
> `~/.traycer/cli-agents/` though Kilo CLI was retired 2026-07-19. Decide whether
> `generate_kilo_agents.py` should stay in `daily_refresh.sh`.

---

## 5. Per-project configuration

| Scope | Count | Function |
|---|---|---|
| `/opt/*/CLAUDE.md` | 51 | Project instructions; governance-synced from `/opt/fabrik` |
| `/opt/*/.claude/` | 51 | Project-scoped `settings.json`, `hooks/`, `worktrees/` |
| `~/scratch/inbox-zero/` | 1 | A 52nd project config outside `/opt` — its own `CLAUDE.md` + `.claude/{agents,skills}` |

Example — `/opt/fabrik/.claude/`: `settings.json`, `hooks/final_gate_stop.py` (the Stop-hook that
enforces the definition-of-done gate — per-file failure attribution so a sibling session's
ATTRIBUTED shared-tree dirt reports instead of blocking (a failure citing no
attributable path stays indeterminate and can still block up to the 3-attempt cap); its third cause
catches checkpoint-stalls: first-person promises, permission questions a session-owned active plan
already answers, and passive obligations ("Pass 7 is owed") with no same-turn dispatch),
`hooks/skill_router.py` (the UserPromptSubmit router: bare-prose EN/TR prompts get a "this matches
/fabrik-X — invoke or say why not" nudge; Haiku fallback tier is opt-in via `FABRIK_ROUTER_HAIKU=1`),
`hooks/session_orient.py` (SessionStart ORIENT block: binds the synced CLAUDE.md, surfaces MEMORY.md
state, names session-recall + the enforcement mesh; fail-open), `worktrees/`. All three hooks +
`settings.json` are fleet-synced via `AGENT_HOOK_FILES` (`scripts/fabrik_synced_manifest.py`).
Note the CLAUDE.md split: a PROJECT's `CLAUDE.md` is the synced copy of the hub's
`templates/governance/CLAUDE.md`; the hub's own `/opt/fabrik/CLAUDE.md` is a distinct platform-repo
contract (never distributed).

---

## 6. Windows-side surfaces (`/mnt/c/Users/user/`)

A second, independent configuration surface. Existence verified; liveness is by mtime only.

| Path | Function | Last written |
|---|---|---|
| `AppData\Roaming\Claude\claude_desktop_config.json` | **Claude Desktop** MCP config — 8 servers: `c-drive`, `desktop-commander`, `fabrik-citation-verifier`, `onedrive-docs`, `vault-write`, `windows-mcp`, `wsl-filesystem`, `wsl-shell` (+ 3 dated backups) | 2026-07-23 |
| `AppData\Roaming\Claude\` | Desktop app state: `claude-code` (254 MB), `claude-code-vm`, `Cache`, `blob_storage`, `ChromeNativeHost`, `ant-device-registry.json`, `bridge-state.json` | 2026-07-26 — **active** |
| `.claude.json` + `.claude - bckp.json`, `.backup`, `.before-fabrik-fix`, `.before-http-fabrik`, `.tmp.*` | Windows-side CLI config + 5 backups | 2026-07-17 |
| `.claude/` | Windows-side Claude dir | — |
| `AppData\Local\Claude` | Desktop local data | 2026-04-05 |
| `AppData\Local\Claude-3p`, `Claude Nest-3p` | Third-party/nest variants | 2026-04-30 — dormant |
| `.claude-panel` | Older panel tooling | 2026-05-20 — dormant |
| `.claude-server-commander`, `-logs` | Retired MCP server-commander (WSL twin at `~/.claude-server-commander`, last write 2025-11-07) | 2025-10-28 — dormant |

---

## 7. MCP servers

**WSL CLI (`~/.claude.json`) — 18:** `brave-search` · `chrome-devtools` · `context7` · `exa` ·
`fabrik-citation-verifier` · `firecrawl` · `github` · `grafana` · `maestro` · `magicui` ·
`media-engine` · `mobile-mcp` · `playwright` · `postgres-pro` · `pubchem` · `serena` ·
`session-recall` · `shadcn`

**Claude Desktop (Windows) — 8:** listed in §6. `wsl-shell` is **Desktop-only** — see
[wsl-shell-mcp-setup.md](wsl-shell-mcp-setup.md). `fabrik-citation-verifier` is the only server on both
surfaces (HTTP transport — see [MCP_HTTP_TRANSPORT.md](MCP_HTTP_TRANSPORT.md)).

---

## 8. Size summary & prune candidates

| Item | Size | Note |
|---|---|---|
| `~/.claude/projects/` | 6.9 GB | Session transcripts — `session-recall`'s source corpus; prune only with retention in mind |
| `~/.cache/claude-cli-nodejs/` | 3.4 GB | Safe to clear; rebuilt on demand |
| `~/.claude/file-history/` | 2.2 GB | Edit undo history; nothing prunes it automatically |
| `~/.claude-youtube-headless/` | 2.0 GB | **Do not touch** while the youtube RAG pipeline runs |
| `~/.local/share/claude/versions/` | 523 MB | Two superseded versions (2.1.218, 2.1.220) |
| `~/.claude/plugins/` | 163 MB | Marketplace clones |
| `~/.claude/session-env/` | 186 MB / 46,789 entries | Entry count is the cost |
| `~/.claude/telemetry/` | 141 MB | Upload queue |

Cleanup mechanics live in [cleanup-automation.md](cleanup-automation.md); open items in
[cleanup-maintenance-backlog.md](cleanup-maintenance-backlog.md).

---

## Related

[wsl-startup-inventory.md](wsl-startup-inventory.md) · [session-recall.md](session-recall.md) ·
[vscode-configuration.md](vscode-configuration.md) · [wsl-shell-mcp-setup.md](wsl-shell-mcp-setup.md) ·
[MCP_HTTP_TRANSPORT.md](MCP_HTTP_TRANSPORT.md) · [WSL2-DNS-FIX.md](WSL2-DNS-FIX.md) ·
[../operations/wsl-environment.md](../operations/wsl-environment.md)
