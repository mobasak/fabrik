# Claude Config — Backup & Restore

DR mirror of this box's Claude configuration to the **private GitHub DR store**, with point-in-time
restore. Sibling of the credential mirror (`dr_env_backup.sh`) — same store, same discipline.

**Script:** `/opt/fabrik/scripts/dr_claude_backup.sh` · **Store:** `/opt/fabrik-dr-store/claude-config/`
→ `github.com/mobasak/fabrik-dr-store` (**private**) · **Inventory of what exists:**
[claude-configuration-inventory.md](claude-configuration-inventory.md)

---

## Why git, not B2

| | git (private repo) | B2 / restic |
|---|---|---|
| Payload | ~950 KB of text config — git's sweet spot | Built for blobs |
| Versioning | **Every change is a commit**; nothing overwrites its predecessor | Snapshots + retention policy |
| "What changed?" | `git diff` between any two points | Restore both, diff manually |
| Revert one file to last week | `git checkout <sha> -- <path>` | Full snapshot restore + copy out |
| Restore tooling | git (already everywhere) | restic binary + repo password + B2 creds |
| Off-box | GitHub | Backblaze |
| Already proven here | Yes — `dr_env_backup.sh` + weekly recovery test | Yes, for **VPS data** (Backrest, port 9898) |

**B2/Backrest stays the right tool for the VPS's large mutable data** (Postgres, volumes). For a
sub-megabyte text-config set where the whole point is *"revert to how it was before that change"*,
git wins outright — and reuses machinery already running and already recovery-tested.

---

## What is mirrored

Small, hand-maintained, **not regenerable from any other repo**:

| Source | Stored as |
|---|---|
| `~/.claude.json` | `claude.json` (normalized) |
| `~/.claude/settings.json` | `claude/settings.json` |
| `~/.claude/agents/*.md` (4) | `claude/agents/` — **exist only here**, no other copy on earth |
| `~/.claude/bin/**` | `claude/bin/` — hand-built hook helpers (`claude-sound.sh`, `claude-stop-decider.py`), **exist only here** |
| `~/.claude/.credentials.json` | `claude/credentials.json` 🔐 |
| `~/.claude/manager-accounts/**` (3 accounts) | `claude/manager-accounts/` 🔐 |
| `~/.claude/.claude-manager/*.{json,js}` | `claude/.claude-manager/` (minus ephemeral `active-sessions.json`) |
| `~/.claude/plugins/*.json` | `claude/plugins/` |
| `~/.claude-youtube-headless/{.claude.json,settings.json}` | `claude-youtube-headless/` (normalized) |
| Windows `claude_desktop_config.json` | `windows/claude_desktop_config.json` |

Plus `MANIFEST.txt` — host, Claude version, MCP-server count, agent count, account count.

**Deliberately NOT mirrored:** `commands/` + `skills/fab-*` (rendered from
`/opt/fabrik/commands/_sources`, already in git) · `projects/` `file-history/` `session-env/`
`telemetry/` (~9 GB of session state) · `plugins/marketplaces/` (git clones, re-fetchable) · caches,
logs, `*.lock`, `*.bak`, `*.tmp.*`.

🔐 The store holds live OAuth tokens and account credentials. It is a **private** repo and already the
home of the fleet `.env` mirror — same trust boundary. Never make it public; never mirror it elsewhere.

### JSON normalization
`.claude.json` is rewritten constantly with reordered keys and volatile counters (`usageCount`,
`lastUsedAt`, `lastCost`, `numStartups`, …). The script normalizes on mirror — sorted keys, volatile
keys dropped — so **a diff shows only real config change** and repeated runs are true no-ops.

---

## Schedule

| Trigger | When |
|---|---|
| Daily cron | `45 3 * * *` |
| Reboot catch-up | `@reboot sleep 90 && …` |
| Manual | `/opt/fabrik/scripts/dr_claude_backup.sh` |

Log: `/var/log/dr-claude-backup.log`. A run with no real change **commits nothing** — the previous
snapshot stands.

---

## Restore

### Everything, from the latest snapshot
```bash
/opt/fabrik/scripts/dr_claude_backup.sh --restore
```
The live state is copied to `~/.claude-restore-backup-<UTC>/` **first** — a restore never clobbers
blind, so a wrong restore is itself revertible. `.credentials.json` is re-chmod'd to `600`.
**Restart Claude Code** (and Claude Desktop if its config changed) afterwards.

### From a point in time
```bash
cd /opt/fabrik-dr-store && git log --oneline -- claude-config     # pick a snapshot
/opt/fabrik/scripts/dr_claude_backup.sh --restore --from <sha>
```

### One file only (the common case — "undo yesterday's settings edit")
```bash
cd /opt/fabrik-dr-store
git log --oneline -- claude-config/claude/settings.json
git show <sha>:claude-config/claude/settings.json > ~/.claude/settings.json
```

### From a dead box (bare-metal recovery)
```bash
git clone git@github.com:mobasak/fabrik-dr-store.git /opt/fabrik-dr-store
cp /opt/fabrik-dr-store/claude-config/claude.json                 ~/.claude.json
mkdir -p ~/.claude
cp -a /opt/fabrik-dr-store/claude-config/claude/. ~/.claude/
mv ~/.claude/credentials.json ~/.claude/.credentials.json && chmod 600 ~/.claude/.credentials.json
# then re-render the generated layer from the fabrik repo:
cd /opt/fabrik/commands && python3 assemble_commands.py     # restores commands/ + skills/
```

---

## Verifying it works

```bash
/opt/fabrik/scripts/dr_claude_backup.sh                      # 1. run
cd /opt/fabrik-dr-store && git log --oneline -3 -- claude-config   # 2. snapshot exists
/opt/fabrik/scripts/dr_claude_backup.sh                      # 3. "no change" (idempotent)
cat /opt/fabrik-dr-store/claude-config/MANIFEST.txt          # 4. sane counts
```

Round-trip verified 2026-08-03: an agent definition was corrupted, restored, and came back
**byte-identical (md5 match)**.

---

## Keeping it current

The mirror only knows what the script lists. **After adding a new config surface** — a new
`~/.claude/agents/*.md`, a new profile dir, a new hand-maintained config file — add it to the
`do_backup()` mirror list, run the script once, and confirm the file appears under
`/opt/fabrik-dr-store/claude-config/`. Also update
[claude-configuration-inventory.md](claude-configuration-inventory.md).

---

## Related

[claude-configuration-inventory.md](claude-configuration-inventory.md) ·
[../operations/credential-recovery.md](../operations/credential-recovery.md) (the `.env` sibling) ·
[cleanup-automation.md](cleanup-automation.md)
