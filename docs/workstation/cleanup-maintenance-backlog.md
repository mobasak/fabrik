# Workstation Cleanup & Maintenance Backlog

**Date:** 2026-07-25
**Status:** 🟡 OPEN ITEMS — the big cleanup is done (~90 GB reclaimed); this tracks what's left.
**Affects:** Local WSL2 dev box (Ubuntu-24.04) + its Windows host. NOT the VPS fleet.

---

## Automation now in place (no action needed — FYI)

- **Weekly cleanup cron** — `~/.local/bin/wsl-cleanup.sh --no-windows`, Mondays 09:30
  (logs to `~/.local/share/wsl-cleanup.cron.log`). Prunes package caches (uv/pip/npm/pnpm/pre-commit),
  VS Code server logs, Kilo logs/snapshots, Docker dangling images, journal. `--no-windows` = never
  touches any `.vhdx`. Run `wsl-cleanup.sh --dry-run` to preview, or without `--no-windows` for the
  Windows-side swap/crash-dump sweep.
- **`.wslconfig`** — swap pinned to `C:\wsl\swap.vhdx` (no more orphaned swaps in `%TEMP%`);
  risky `sparseVhd=true` removed (Microsoft flagged it as data-corruption risk); `autoMemoryReclaim=gradual` kept.
- **Compaction script** — `compact-wsl.bat` on the Desktop (uses Optimize-VHD; see item A1 for why it barely helps).

---

## A. Disk reclaim — optional / deferred

- **A1. WSL `ext4.vhdx` compaction (~65 GB dead air).** File is 316 GB; real usage ~250 GB.
  `diskpart compact` and `Optimize-VHD -Mode Full` **both confirmed ineffective** — WSL2 does not
  propagate `fstrim` discard down to deallocate vhdx blocks, so nothing to reclaim. The **only** reliable
  method is a full **`wsl --export` → `--unregister` → `--import`** rebuild (tar → `D:\`, 704 GB free).
  Heavy op (~250 GB moved twice); resets default user (restore via `/etc/wsl.conf` `[user] default=ozgur`
  or `wsl --manage --set-default-user`). C: currently has ample free space, so this is optional.
  *Note:* a full export tar contains everything — all `/opt` projects, crontab (incl. secrets), `.bashrc`, services.

- **A2. ~10 GB Docker images behind 8 stopped test containers.** Removing the stacks unlocks the images:
  `wpf-test-{nginx,wp,mariadb}`, `tojlo-{rag,rls,phase0}`, `crm-dev-postgres`, `ti-dev-pg` (all `Exited 255`).
  Then `docker image prune -a` reclaims. ⚠️ `crm-dev-postgres` / `ti-dev-pg` / `wpf-test-*` exited only
  ~10h ago — may be active dev stacks. Confirm before removing.

- **A3. nvm `v22.22.2` (~412 MB).** Kept because it currently hosts **7 live MCP servers**
  (episodic-memory, chrome-devtools-mcp, etc.). After the **next Claude Desktop / VS Code restart**, those
  relaunch under Node 24.18 (the new default) → then remove with `nvm uninstall 22.22.2`. Verify MCPs work first.

---

## B. Confirm-first personal files (owner decision)

- **B1.** `~/traycer-report-panel` (51 MB, Mar 2026) — old, superseded?
- **B2.** `~/m365-venv` (37 MB, Dec 2025) — stale venv; keep only if the M365 script is still used.
- **B3.** `~/financian_claims.jsonl` (1 MB) — data dump; check before removing.
- **B4.** `~/youtube_downloader.py` + `~/setup_youtube_downloader.sh` (18 KB, Nov 2025) — orphan scripts.
- **B5.** Old dotfile `*.backup` files (`.bashrc.backup`, `.claude.json.backup*`, `start-mcp-shell.sh.backup×2`,
  `.gitconfig.backup`, `.npmrc.backup`) — consolidate into `~/backups/`.
- **B6.** Windows `Downloads` — 2020-onward installers left for review (only pre-2020 + the Adobe zip were removed).
- **B7.** Windows Devin CLI remnants (~750 KB): `AppData\Local\devin` + `AppData\Roaming\devin` — remove if Devin CLI unused.

---

## C. Follow-ups tied to your own fixes

- **C1. calendar-orchestration cron + dead `FACTORY_API_KEY`.** You're keeping the weekly cron (Sun 02:00) to
  swap Factory for another provider. Until then it fails (Factory dropped → key invalid). When you fix it,
  **remove the hardcoded `FACTORY_API_KEY` from the crontab line** (secret in plaintext in `crontab -l`).

- **C2. grafana-MCP orphan reaper.** The `mcp/grafana` containers leak on MCP reconnect churn (config already
  has `--rm`; orphans stay "Up" after ungraceful disconnects, so `--rm` never fires). Harmless (~0 disk). Optional:
  add a reaper line to `wsl-cleanup.sh` to remove idle `mcp/grafana` containers.

- **C3. Grafana service-account token** sits in plaintext in `~/.claude.json` (grafana MCP `env` block). Normal for
  MCP configs; noted for awareness.

---

## D. Separate governance task (`/opt/fabrik` — NOT workstation cleanup)

- **D1. `.windsurfrules` + Cascade-executor references.** `.windsurfrules` is in `fabrik_synced_manifest.py` →
  propagates to all 41 projects; `select_rules.py` + rule-pack docs still name **Cascade** as an executor though it's
  retired. ⚠️ **The `.windsurf/rules/` FOLDER content is LIVE governance — keep it.** Only the single legacy
  `.windsurfrules` file + stale Cascade-executor prose are candidates. This is a deliberate fleet-wide change →
  its own focused task through the fabrik pipeline (upstream edit + gate + review), not a workstation chore.

---

## Done this session (reference)

- **~90 GB reclaimed:** Windsurf/Codeium + Devin desktop + Zed (WSL+Windows) + Traycer update residue +
  Windows Temp (27 GB crash dumps + ~32 GB orphaned WSL swaps) + package caches + `.factory` + Docker images/volumes.
- **Node consolidated to 24.18.0** as the interactive default; globals (eas-cli, MCP filesystem, higgsfield) migrated;
  removed nvm v20 + v24.16. **System `/usr/bin/node` kept at v22.23** on purpose — the wsl-shell MCP's node-pty
  native module is built against it (major upgrade would break the Claude-Desktop→WSL bridge).
- **Services:** removed dead `enforce-windsurfrules.service` (boot symlink), removed retired `supabase-keepalive`
  (trade-intelligence migrated), **disabled `ollama` auto-start** (511 MB RAM freed; all 71 GB of models kept on disk —
  start manually with `sudo systemctl start ollama`).
- All edited configs backed up under `~/backups/` (`.wslconfig.backup.*`, `.bashrc.backup.*`, `windsurf-config-*`).
