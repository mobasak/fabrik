# Workstation Cleanup & Maintenance Backlog

**Date:** 2026-08-03 · **Validated live:** 2026-08-30 (all three automation pieces proven running; numbers below refreshed)
**Status:** 🟡 OPEN ITEMS — the big cleanup is done (~90 GB reclaimed); this tracks what's left.
**Affects:** Local WSL2 dev box (Ubuntu-24.04) + its Windows host. NOT the VPS fleet.

---

## Automation now in place (no action needed — FYI)

- **Cleanup automation** — one cleaner per OS side + a manual compaction tool. Full reference:
  [cleanup-automation.md](cleanup-automation.md). In short: `cache-prune.sh` (WSL, cron Sun 03:00),
  `cleanup-weekly.ps1` (Windows, `Fabrik-WeeklyCleanup` task), `compact-wsl.bat` (manual vhdx compaction).
- **`.wslconfig`** — swap pinned to `C:\wsl\swap.vhdx` (no more orphaned swaps in `%TEMP%`);
  risky `sparseVhd=true` removed (Microsoft flagged it as data-corruption risk); `autoMemoryReclaim=gradual` kept.

---

## A. Disk reclaim — optional / deferred

- **A1. WSL `ext4.vhdx` compaction (~200 GB dead air as of 2026-08-30).** File is now 555 GB
  (`C:\Users\user\AppData\Local\wsl\{4719c2ec-…}\ext4.vhdx`); real in-guest usage 355 GB
  (was 358 GB physical / 277 GB used on 2026-08-03 — the gap widened ~120 GB in a month).
  `diskpart compact` and `Optimize-VHD -Mode Full` **both confirmed ineffective** — WSL2 does not
  propagate `fstrim` discard down to deallocate vhdx blocks, so nothing to reclaim. The **only** reliable
  method is a full **`wsl --export` → `--unregister` → `--import`** rebuild (tar → `D:\`).
  Heavy op (~277 GB moved twice); resets default user (restore via `/etc/wsl.conf` `[user] default=ozgur`
  or `wsl --manage --set-default-user`). C: currently has ample free space, so this is optional.
  *Note:* a full export tar contains everything — all `/opt` projects, crontab (incl. secrets), `.bashrc`, services.

- **A2. Stopped test containers — ✅ DONE (2026-08-03).** No stopped containers remain: `wpf-test-*` and
  `tojlo-*` are gone; `crm-dev-postgres` and `ti-dev-pg` turned out to be live dev stacks and are running.
  Residual image slack 2026-08-30: 12.5 GB reclaimable of 17.9 GB (25 images, 8 active) — the weekly
  prune removes DANGLING only by design, so tagged-unused images accumulate; still no manual action owed.

- **A3. nvm `v22.22.2` (412 MB).** No longer hosts any MCP server — every MCP in `~/.claude.json` and in
  Claude Desktop's config runs under `/usr/bin/node`, `npx`, or a venv. The one remaining consumer is the
  youtube docs-site job, which pins `PATH=…/v22.22.2/bin` in its `npm start` wrapper. Repoint that wrapper
  at Node 24.18, then remove with `nvm uninstall 22.22.2`.

---

## B. Confirm-first personal files (owner decision)

- **B1.** ✅ DONE (2026-08-03) — `~/traycer-report-panel` removed (Traycer retired).
- **B2.** ✅ DONE (2026-08-03) — `~/m365-venv` removed (M365 runs via the claude.ai connector).
- **B3.** ✅ DONE (2026-08-03) — archived to `~/old-residue-20260803/` (reversible).
- **B4.** ✅ DONE (2026-08-03) — archived to `~/old-residue-20260803/`.
- **B5.** ✅ DONE (2026-08-03) — loose `~` backups archived to `~/old-residue-20260803/`; `~/.claude-fab-shim-backup-20260721/` + `~/fabrik-traycer-backups/` removed.
- **B6.** Windows `Downloads` — 2020-onward installers left for review (only pre-2020 + the Adobe zip were removed).
- **B7.** ✅ DONE (2026-08-03) — no `devin` dirs remain under `/mnt/c` (already removed).

---

## C. Follow-ups tied to your own fixes

- **C1.** ✅ DONE (2026-08-03) — Factory is retired: the weekly cron line (Sun 02:00, plaintext `FACTORY_API_KEY`) was removed (crontab backed up to `~/backups/`). NOTE for the calendar-orchestration-engine owner: its `enrichWithAI/classifyWithAI/curateEvents` scripts still reference `FACTORY_API_KEY` — the pipeline needs an OpenRouter migration before it can run again.
- **A4. Dangling docker volumes — 62.5 GB reclaimable (measured 2026-08-30, the one real accumulating leak).**
  852 dangling anonymous volumes (was 534 on 08-22, 847 on 08-30 — `cache-prune.sh` reports them weekly by
  design and never deletes, and the NOTE has had no reader). All are unreferenced anon hashes from dev
  compose stacks; 3 named volumes are active and untouched by any prune. OPERATOR-GATED (volume deletion
  is data-destructive): dry-run review `docker volume ls -f dangling=true`, then `docker volume prune -f`
  reclaims the 62.5 GB. Until approved, the weekly NOTE keeps counting.

- **C2. grafana-MCP orphan reaper.** The `mcp/grafana` containers leak on MCP reconnect churn (config already
  has `--rm`; orphans stay "Up" after ungraceful disconnects, so `--rm` never fires). 10 are up right now, the
  oldest ~18h. Harmless (~0 disk). Optional: add a reaper line to `~/.local/bin/cache-prune.sh` to remove idle
  `mcp/grafana` containers — note `docker container prune` never touches them because they never stop.

- **C3.** ACCEPTED (2026-08-03) — the Grafana token in `~/.claude.json` is required by the grafana MCP; per the single-operator threat model this is accepted, not a to-do.
  MCP configs; noted for awareness.

---

## D. Separate governance task (`/opt/fabrik` — NOT workstation cleanup)

- **D1. `.windsurfrules` + Cascade-executor references.** `.windsurfrules` is in `fabrik_synced_manifest.py` →
  propagates to all 42 `/opt/*` projects; `select_rules.py` + rule-pack docs still name **Cascade** as an executor though it's
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
