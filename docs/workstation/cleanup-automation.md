# Cleanup Automation — WSL + Windows

**Date:** 2026-08-03
**Status:** ✅ CURRENT
**Affects:** Local dev box (WSL2 `Ubuntu-24.04`) + its Windows host. NOT the VPS fleet.

Three pieces, cleanly split so nothing overlaps: **one cleaner per OS side** (scheduled) + **one manual
compaction tool**.

| Piece | Where | Schedule | Owns |
|---|---|---|---|
| `cache-prune.sh` | `~/.local/bin/` (WSL) | cron **Sun 03:00** | WSL caches, Docker, logs, journal |
| `cleanup-weekly.ps1` | `C:\Users\user\scripts\` (Windows) | Task Scheduler `Fabrik-WeeklyCleanup`, **Sun 04:00** | Windows Temp, crash dumps, WU downloads |
| `compact-wsl.bat` | `C:\Users\user\OneDrive - Tojlo Solutions LLC\Desktop\` | manual | WSL vhdx compaction |

---

## A. WSL cleaner — `~/.local/bin/cache-prune.sh`

- **Cron:** `0 3 * * 0` (Sundays 03:00) → logs to `~/.cache/cache-prune.log`.
- **Run manually anytime:** `cache-prune.sh`
- **Design:** threshold-based — a cache is cleared **only when it exceeds a size cap**, so it never forces
  needless re-downloads. Never touches source/data, `~/.local`, or the costly-to-refetch caches
  (`huggingface`, `ms-playwright`, `claude-cli-nodejs`).

What it does each run:

- **Package caches (capped):** npm >3G · uv >2G · pip >2G · selenium >2G · puppeteer >1G · `pre-commit gc`
- **Docker (safe):** dangling-image prune · build-cache prune · stopped-container prune (>14d) ·
  dangling-volume **reporting only** (volumes are never auto-deleted — data lives there)
- **Logs / session dirs:** VS Code server logs (>1d) + VSIX cache · Kilo `log/` + `.cache/kilo/packages`
  (Kilo `snapshot/` **age-gated >7d** — may hold checkpoint-restore state; `kilo.db` kept) · journal vacuum to 200M

**⚠️ Catch-up caveat:** plain cron has **no catch-up** (`anacron` is not installed). If WSL is down at
Sun 03:00 the run is skipped until the next Sunday. Mitigations: run `cache-prune.sh` by hand, **or** convert
the schedule to a **systemd timer with `Persistent=true`** (systemd is enabled here) which runs a missed job
on next boot. *Do NOT* host it in `/opt/fabrik/scripts/wsl_startup_hook.sh` — that file is git-tracked fabrik
infra, not a place for personal-box cleanup.

---

## B. Windows cleaner — `C:\Users\user\scripts\cleanup-weekly.ps1`

- **Schedule:** Windows Task Scheduler task **`Fabrik-WeeklyCleanup`** (weekly, Sun 04:00), logs to `…\scripts\cleanup-weekly.log`.
- **Preview (deletes nothing):** `powershell -File cleanup-weekly.ps1 -DryRun`
- **Design:** age-gated deletion — never removes anything a running process might still reach for.

What it does:

- WSL crash dumps (`%LOCALAPPDATA%\Temp\wsl-crashes`, >2d)
- General `%TEMP%` (>7d — the gate protects in-flight installers/updaters)
- App CrashDumps (>7d) + `C:\Windows\Minidump` (>7d)
- Windows Update download leftovers (`SoftwareDistribution\Download`, >14d)
- npm + pip cache

This owns the **Windows** side; the WSL cleaner never touches `/mnt/c`. The two never overlap.

---

## C. Manual compaction — `compact-wsl.bat` (Desktop)

- **Manual only** (closes VS Code + Docker, shuts WSL down — can't run while WSL is in use).
- Trims free space (`fstrim`), then `Optimize-VHD -Mode Full` (read-only mount → cannot alter data).
- **Reality check:** WSL2 does **not** propagate `fstrim` discard down to deallocate vhdx blocks, so both
  `Optimize-VHD` and `diskpart compact` reclaim only a fraction. The **only** method that truly shrinks the
  disk is a full `wsl --export` → `--unregister` → `--import` rebuild (see
  [cleanup-maintenance-backlog.md](cleanup-maintenance-backlog.md) item A1). The `.bat` is kept for the
  occasional nibble; the export/import is the real lever when the vhdx genuinely needs shrinking.

---

## Notes

- **Backups:** every edited config/script is copied to `~/backups/` before changes
  (`cache-prune.sh.backup.*`, `crontab.backup.*`, `.wslconfig.backup.*`, `.bashrc.backup.*`).
- **`.wslconfig`:** swap pinned to `C:\wsl\swap.vhdx` (no more orphaned swaps in `%TEMP%`); the risky
  experimental `sparseVhd` flag is not set (Microsoft flags sparse mode as a data-corruption risk).
- **Related:** [cleanup-maintenance-backlog.md](cleanup-maintenance-backlog.md) (remaining items) ·
  [wsl-startup-inventory.md](wsl-startup-inventory.md) (what runs on boot).
