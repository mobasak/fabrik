# Cleanup Automation — WSL + Windows

**Date:** 2026-08-03 · **Updated:** 2026-09-03 (§ D — the subagent spools, and why they are not swept)
**Status:** ✅ CURRENT
**Affects:** Local dev box (WSL2 `Ubuntu-24.04`) + its Windows host. NOT the VPS fleet.

Three pieces, cleanly split so nothing overlaps: **one cleaner per OS side** (scheduled) + **one manual
compaction tool**. § D is the standing DO-NOT-SWEEP list and § E the one scheduled task that legitimately
empties a spool — both kept here because
this page is where a new cleanup rule gets written.

| Piece | Where | Schedule | Owns |
|---|---|---|---|
| `cache-prune.sh` | `~/.local/bin/` (WSL) | cron **Sun 03:00** | WSL caches, Docker, logs, journal |
| `cleanup-weekly.ps1` | `C:\Users\user\scripts\` (Windows) | Task Scheduler `Fabrik-WeeklyCleanup`, **Sun 04:00** | Windows Temp, crash dumps, WU downloads |
| `compact-wsl.bat` | `C:\Users\user\OneDrive - Tojlo Solutions LLC\Desktop\` | manual | WSL vhdx compaction |
| `flush_subagent_outboxes.py` | `/opt/fabrik/scripts/kilo-benchmarks/` (WSL) | **daily 06:00** via `daily_refresh.sh` **+ every boot** via `wsl_startup_hook.sh` | drains `.tmp/subagents/pg_outbox*.jsonl` — see § E |
| `scratch_sweep.py --dead --apply` | `/opt/fabrik/scripts/` (WSL) | cron **04:20 daily** — ⚠️ **NOT YET PLACED**: crontab writes are classifier-blocked, so the line is handed to the operator | DEAD sessions' scratch under `/tmp/claude-<uid>` — see § F |

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

## E. The one scheduled task that DOES empty a spool — `flush_subagent_outboxes.py`

The § D files are not swept, but `pg_outbox.jsonl` does get emptied — by a **transport**, not a
cleaner. That distinction is the whole point: `cache-prune.sh` deletes regenerable bytes; this
**moves** run records into Postgres and only then removes the local copy.

- **Schedule:** daily **06:00** as a step in `daily_refresh.sh`, **and on every boot** via
  `wsl_startup_hook.sh`. Both entry points share `/tmp/.fabrik_daily_<UTC>`, so whichever runs first
  that day makes the other skip entirely — which is why the step must exist in **both**. It was in
  `daily_refresh.sh` alone until 2026-09-03, so on every boot-wins day the spools never drained;
  guarded now by `test_both_entry_points_flush_before_they_rank`.
- **What it does:** walks every `<repo>/.tmp/subagents/` under `/opt` depth-unbounded, and for each
  loops `flush_outbox` until it returns 0 — `.flushing` residuals and the live outbox are separate
  files, so one call per directory is not enough. Receipts are written back to the **owning** repo.
- **Verified 2026-09-03 (first unattended run):** 250 of 250 pending rows flushed across 3 dirs; the
  two non-empty ones needed `rounds 2`, so the loop is load-bearing, not defensive.
- **Fail-open on purpose:** the script returns 0 on every internal path, including an empty outbox, so
  a non-zero exit means the interpreter or an import failed — never "nothing to flush". Both entry
  points alert on non-zero, because the ranking step runs immediately after and would otherwise
  publish `TASK_SUBAGENT_SELECTION.md` from an incomplete ledger.
- **Why it belongs on this page:** without it the outboxes only grow. Only four repos hold a
  `SUBAGENT_RUNS_DSN`; for every other repo this task is the sole path from a local spool file to the
  database, and it is what lets § D mark those files NEVER-delete without them accumulating forever.

⚠️ **Not a cleanup knob.** Do not add age gates, size caps, or `find -delete` to the spools it manages —
an unflushed row is the only copy of a run that happened. § D's table is the contract.

---

## F. Session scratch and agent worktrees — `scratch_sweep.py`

The one cleaner an AGENT runs on its own work, and the only one that removes anything under
`/tmp/claude-<uid>`. Landed 2026-09-08 (plan `2026-09-08-plan-1-scratch-sweep`, D-184/D-187) because
no rule had ever said whose job this was: nothing in any `CLAUDE.md`, no close-out step, no hook, no
janitor — `git worktree remove` lived only as unenforced prose. The residue reached 87 GB before a
manual clear, and the manual clear is exactly the failure mode § A's design principle warns about.

**Three modes, and the dry run is the default in every one:**

```bash
python3 /opt/fabrik/scripts/scratch_sweep.py                 # this session's scratchpad — a table
python3 /opt/fabrik/scripts/scratch_sweep.py --apply         # remove what it listed as `stale`
python3 /opt/fabrik/scripts/scratch_sweep.py --worktrees     # this repo's agent worktrees
python3 /opt/fabrik/scripts/scratch_sweep.py --dead          # the janitor, DRY RUN
python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply  # what the cron line runs
```

Every row carries a class, a reason and its evidence; `--apply` is opt-in and prints the refusal set
before it removes anything. The operator's two constraints are the whole design: *"we should not
cause data loss"* and *"agents must know what will this script do while using it."*

**Its relation to § D is the point.** § D's DO-NOT-SWEEP list exists because a rule globbing
`.tmp/**` would take `pg_outbox.jsonl` with it. This tool's scan roots are `/tmp/claude-<uid>` and
the paths `git worktree list` reports — **`<repo>/.tmp` is never a scan root**. A worktree git itself
registers under `<repo>/.tmp` (fabrik-lib has one) is classified like any other worktree and spared
by the ordinary guards; it is never swept as a spool. And because `git worktree remove` deletes
ignored files even without `--force`, a worktree holding ignored DATA outside the cache allowlist is
`wt-ignored-data` and is never removed — which is what keeps § D's spools safe on that path too.

**What it never touches** (hard-coded, printed by `--help` and by every apply run): repo files, except
a worktree it classified removable · transcripts and `~/.claude*/state`, beyond the one lock file it
creates · `<repo>/.tmp/**` as a scan root · docker anything · another LIVE session's scratch · the
session's own `tasks/` dir · a symlink's target · a worktree another session registered, one holding
ignored data, or one git does not register · anything holding a backup shape (`*.bak`, `*.original`,
`*pristine*`, `before.txt`/`after.txt`, `.keep`) — the entry's own NAME included, which is what keeps
the operator's `pristine/` and `fe-pristine/` baselines.

**Why the janitor needs three signals.** A sid is `dead` only when it has no live signal, AND a death
signal, AND its own directory is idle past 7 days. A gone pid is NOT a finished session: `--resume`
keeps the sid across exactly the network deaths, context fills and quota holds this tool serves.
Measured 2026-09-08: 18 sids had a gone-pid sessions file and a live directory, and all 18 were
younger than 7 days — one of them 8 minutes old.

**The cron line, for the operator to place (it is NOT in the crontab yet — `crontab -l` has no
04:20 entry, and a crontab write is classifier-blocked for an agent):**

```cron
20 4 * * * python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply >> $HOME/.claude/scratch-sweep.log 2>&1
```

**⚠️ It carries NO `flock -n` wrapper, deliberately.** The script takes that lock itself,
and `flock(1)` holds it across the exec — so a wrapper on the same path makes the child's own
non-blocking acquire fail and the janitor exits 0 having swept nothing, silently, every night.
Reproduced 2026-09-08.

**Test seams** (env vars, all with production defaults): `SCRATCH_SWEEP_ROOT` · `SCRATCH_SWEEP_NOW`
· `SCRATCH_SWEEP_SESSIONS_DIRS` · `SCRATCH_SWEEP_TRANSCRIPT_DIRS` · `SCRATCH_SWEEP_BTIME` ·
`SCRATCH_SWEEP_HOOK_BUDGET` · `FABRIK_PROC_ROOT` · `CLAUDE_SOUND_LOCKDIR`, plus
`SCRATCH_SWEEP_FORCE_START`, which is gated behind `SCRATCH_SWEEP_TEST=1` because unlike the others
it can authorize removing another session's worktree. A stray value in an operator's environment
degrades the tool silently, so set none of them outside a test.

Trust the deletion paths because five review rounds found six of them by EXECUTION and each is now
pinned by a test proven red-on-revert: `--include-harness` removing a worktree whose verdict was not
removable, `--include-backups` removing FRESH and HELD backup holders, a dead `/proc` reading as "no
holders", an unreadable sessions root letting a live peer's scratch go, a branch ref truncated at the
last slash deleting an unrelated branch, and a sid-level symlink escaping the scratch root.

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

<!-- BEGIN related-scripts: generated by scripts/render_doc_script_links.py — do not hand-edit -->
## Related scripts

Scripts that declare this document in their `# AFTER-EDIT:` header — editing one of them
means updating this page in the same change. This list is generated from those headers
(`python3 scripts/render_doc_script_links.py`); add the doc to a script's header, not here.

- `scripts/scratch_sweep.py`
<!-- END related-scripts -->
