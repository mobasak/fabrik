# Cleanup Automation — WSL + Windows

**Date:** 2026-08-03 · **Updated:** 2026-09-03 (§ D — the subagent spools, and why they are not swept)
**Status:** ✅ CURRENT
**Affects:** Local dev box (WSL2 `Ubuntu-24.04`) + its Windows host. NOT the VPS fleet.

Three pieces, cleanly split so nothing overlaps: **one cleaner per OS side** (scheduled) + **one manual
compaction tool**. § D is not a fourth piece — it is the standing DO-NOT-SWEEP list, kept here because
this page is where a new cleanup rule gets written.

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

- **Package caches (capped):** npm >3G · `_npx` >1.5G (**no longer wiped unconditionally** — the
  2026-08-30 outage: weekly `_npx` wipe + WSL restart = every window cold-fetching 13 MCP servers past
  the harness's 30 s connect timeout, dead for the whole session; see mcp-roster.md) · uv >2G ·
  pip >2G · selenium >2G · puppeteer >1G · `pre-commit gc`
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

## D. Deliberately NOT cleaned — the subagent spools (`.tmp/subagents/`)

Every repo that dispatches to the OpenRouter pool writes a local spool at `<repo>/.tmp/subagents/`.
**No cleaner touches it, and that is correct** — but the reason belongs here, because the directory
looks exactly like something a cleaner should sweep, and § A and § B are where someone would go to
add that rule.

Measured 2026-09-03: **0.3 GB across 24 dirs** (largest: `fabrik` 72M · `web-ecommerce-factory` 62M ·
`trade-intelligence` 29M). It is **not** a disk-pressure item — it is ~0.04% of the 826 G in use — but
it grows without bound: `libs/subagents/ledger.py` caps the diff *inside a row* (`_MAX_DIFF_CHARS`)
and never rotates or age-gates the FILE, and nothing in `logrotate.d` or `tmpfiles.d` covers it. The
hub's spans 2026-07-08 → today at 18.6 KB/row, because each row embeds the agent's task text plus its
capped diff.

| File | Safe to delete? | Why |
|---|---|---|
| `pg_outbox.jsonl` · `pg_outbox.flushing.jsonl` | **NEVER** | Unflushed run records — the **only** copy until the 06:00 walker inserts them (`daily_refresh.sh` → `flush_subagent_outboxes.py`). Deleting one destroys exactly the runs the flush exists to rescue. Only **four** repos have a `SUBAGENT_RUNS_DSN` at all (measured 2026-09-02 — `fabrik`, `iterative_image_editor`, `trade-intelligence`, `tryton-crm`); for every other repo this file is the sole transport, refilling continuously between drains. |
| `ledger.jsonl` | **No** — not without a retention plan | Read by `check_subagent_flywheel.py` (which `final_gate.py` runs), `kaizen_collect.py`, and `audit_unrecorded()`. Today's refresh reports **1,116 pool runs that ran and were never scored** — listable only from this file. |
| `receipts.jsonl` | **No** | The flush's per-repo audit trail; asserted by `test_flush_subagent_outboxes.py`. |
| `pg_outbox.corrupt.jsonl` | Age-gate it if it ever appears | Quarantined unparseable rows. Absent on every repo as of 2026-09-03. |
| `*.lock` | Yes, if stale | Zero-byte `flock` targets. |

**The trap this section exists to prevent:** a future rule globbing `.tmp/**` or `*.jsonl` would take
`pg_outbox.jsonl` with it, silently, and the loss would look like models that never ran. § A's design
principle — *"never touches source/data"* — already forbids it; the table names the files so nobody
has to re-derive which ones are data.

**If the size ever does start to matter,** the lever is retention inside `libs/subagents/ledger.py`,
**not** a cron `find -delete`: the readers above need the history, so an age gate belongs where the
writer can keep it consistent. That file is vendored — 48 sync-reachable copies, 50 live (D-093) — so
it is a canonical `/opt/fabrik-lib/subagents` edit plus a re-vendor, and needs the operator's
cross-repo word.

---

## Notes

- **Backups:** every edited config/script is copied to `~/backups/` before changes
  (`cache-prune.sh.backup.*`, `crontab.backup.*`, `.wslconfig.backup.*`, `.bashrc.backup.*`).
- **`.wslconfig`:** swap pinned to `C:\wsl\swap.vhdx` (no more orphaned swaps in `%TEMP%`); the risky
  experimental `sparseVhd` flag is not set (Microsoft flags sparse mode as a data-corruption risk).
- **Related:** [cleanup-maintenance-backlog.md](cleanup-maintenance-backlog.md) (remaining items) ·
  [wsl-startup-inventory.md](wsl-startup-inventory.md) (what runs on boot) ·
  `scripts/kilo-benchmarks/flush_subagent_outboxes.py` + `libs/subagents/ledger.py` — the spools
  in § D and the 06:00 flush that drains them.
