# Cleanup Automation — WSL + Windows

**Date:** 2026-08-03 · **Updated:** 2026-09-20 (§ G — RAM, the first non-disk section on this page)
**Status:** ✅ CURRENT
**Affects:** Local dev box (WSL2 `Ubuntu-24.04`) + its Windows host. NOT the VPS fleet.

Cleanly split so nothing overlaps: **one cleaner per OS side** (scheduled) + **one manual
compaction tool** + **one RAM policy** (§ G — every other section on this page is about DISK;
§ G is the only one about memory, and the two are not interchangeable: `~/.cache` is 28 GB on
disk and 0.19 GB in RAM, so deleting it reclaims disk and almost no memory). § D is the standing DO-NOT-SWEEP list and § E the one scheduled task that legitimately
empties a spool — both kept here because
this page is where a new cleanup rule gets written.

| Piece | Where | Schedule | Owns |
|---|---|---|---|
| `cache-prune.sh` | `~/.local/bin/` (WSL) | cron **Sun 03:00** | WSL caches, Docker, logs, journal |
| `cleanup-weekly.ps1` | `C:\Users\user\scripts\` (Windows) | Task Scheduler `Fabrik-WeeklyCleanup`, **Sun 04:00** | Windows Temp, crash dumps, WU downloads |
| `compact-wsl.bat` | `C:\Users\user\OneDrive - Tojlo Solutions LLC\Desktop\` | manual | WSL vhdx compaction |
| `flush_subagent_outboxes.py` | `/opt/fabrik/scripts/kilo-benchmarks/` (WSL) | **daily 06:00** via `daily_refresh.sh` **+ every boot** via `wsl_startup_hook.sh` | drains `.tmp/subagents/pg_outbox*.jsonl` — see § E |
| `scratch_sweep.py --dead --apply` | `/opt/fabrik/scripts/` (WSL) | cron **04:20 daily** — ✅ INSTALLED (verified in `crontab -l` 2026-09-20) | DEAD sessions' scratch under `/tmp/claude-<uid>` — see § F |
| `agent_memory.sh cron` | `/opt/fabrik/scripts/sysadmin/` (WSL) | **hourly** via `weekly_catchup.sh`, fires once a day — ✅ INSTALLED 2026-09-20 | RAM: the four `vm.*` knobs + swap reclaim — see § G |

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
- **`wt-sync-only`** (added 2026-09-15) — every dirty path in the worktree is the governance sync's own materialised output, byte-identical to what the sync would write. Nothing was authored there. ⚠️ It is still NOT removable: `git worktree remove` refuses while untracked files are present and `--apply` never passes `--force`, so this verdict informs rather than promising a removal git would refuse. Remove it by hand with `--force` if you mean to.

**What it never touches** (hard-coded, printed by `--help` and by every apply run): repo files, except
a worktree it classified removable · transcripts and `~/.claude*/state`, beyond the one lock file it
creates · `<repo>/.tmp/**` as a scan root · docker anything · another LIVE session's scratch · the
session's own `tasks/` dir · a symlink's target · a worktree another session registered (unless
`--foreign-older-than`, below), one holding ignored data, or one git does not register · anything
holding a backup shape (`*.bak`, `*.original`,
`*pristine*`, `before.txt`/`after.txt`, `.keep`) — the entry's own NAME included, which is what keeps
the operator's `pristine/` and `fe-pristine/` baselines.

**Why the janitor needs three signals.** A sid is `dead` only when it has no live signal, AND a death
signal, AND its own directory is idle past 7 days. A gone pid is NOT a finished session: `--resume`
keeps the sid across exactly the network deaths, context fills and quota holds this tool serves.
Measured 2026-09-08: 18 sids had a gone-pid sessions file and a live directory, and all 18 were
younger than 7 days — one of them 8 minutes old.

**The cron line — ✅ INSTALLED.** Verified present in `crontab -l` on 2026-09-20; the operator
placed it after this section was written. Kept here because it is the line to restore if the
crontab is ever rebuilt (a crontab write stays classifier-blocked for an agent, so an agent hands
the line over rather than placing it):

```cron
20 4 * * * python3 /opt/fabrik/scripts/scratch_sweep.py --dead --apply >> $HOME/.claude/scratch-sweep.log 2>&1
```

**⚠️ It carries NO `flock -n` wrapper, deliberately.** The script takes that lock itself,
and `flock(1)` holds it across the exec — so a wrapper on the same path makes the child's own
non-blocking acquire fail and the janitor exits 0 having swept nothing, silently, every night.
Reproduced 2026-09-08.

**`--foreign-older-than DURATION` — the dormant-residue flag.** Provenance alone made `--apply` a
guaranteed no-op for the only population the mode exists for: accumulated residue is BY DEFINITION
older than every future session, so the one session permitted to remove it is the one that created
it, and that session is gone. Two repos filed it the same day with the same shape —
web-ecommerce-factory 30 of 30 rows `wt-foreign`, fabrik-lib 10 of 10, oldest 66–68 d. The flag does
not weaken the chain, it lets the chain RUN: a foreign tree older than DURATION is judged on its own
state, and **only a `wt-removable` verdict is promoted** — merged, clean, unlocked, unheld. Every
refusal keeps its own class, which is strictly more informative than the blanket `wt-foreign` it
replaces. Two things it deliberately will not do: a dormant tree whose registration is merely STALE
stays `wt-foreign`, because acting on it runs the REPO-WIDE `git worktree prune` and would drop other
sessions' registrations as a side effect; and a non-positive DURATION is refused (rc 1) rather than
read as "every tree qualifies". Measured on the hub the day it shipped: at `1d`, all 13 rows that had
been `wt-foreign` resolved to `wt-dirty` — each holding an uncommitted `.venv` — and **zero** became
removable. That is the flag working, not failing: the blanket verdict had been hiding the real reason.

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

## G. RAM — `scripts/sysadmin/agent_memory.sh`

Every section above is about DISK. This one is about MEMORY, and it exists because nothing on this
box governed it. Measured 2026-09-20 on a 63 GB host with a 48 GB WSL cap:

- `vm.swappiness` was at its default **60**, so the kernel was about as willing to page out
  anonymous memory as to drop page cache — and it chose badly. **13.9 GB had been swapped out, and
  the processes sitting in swap were MCP servers, VS Code extension hosts and the Kilo extension**
  — the dev infra — while **28 GB of freely-droppable page cache stayed resident**.
- The box was never short of memory: 15.5 GB of anon against a 48 GB cap. It was losing an argument
  with the page-cache heuristic.
- Nothing else sets these knobs. `cache-prune.sh` has zero sysctl lines; `scripts/audit/04-performance.sh`
  only READS `swappiness` and runs on the VPS over SSH, not here.

**The goal is the inverse of a general-purpose server's:** reserve the maximum for Claude sessions,
their MCP servers and their subagents, and let the CACHE be what gets reclaimed.

| Knob | Default | Set to | Why |
|---|---|---|---|
| `vm.swappiness` | 60 | **10** | Prefer dropping cache over swapping agents. Not 0 — that trades swapping for OOM kills, and a 64 GB swap file exists to absorb spikes |
| `vm.vfs_cache_pressure` | 100 | **200** | Reclaim the dentry/inode slab twice as eagerly. This box holds ~1.8 M `ext4_inode_cache` SLAB OBJECTS (1,838,339 on 2026-09-20; ⚠️ not the same metric as `/proc/sys/fs/inode-nr`, which reads ~1.4 M) from walking 46 repos and their worktrees — that gives the kernel something to take that is not an agent |
| `vm.min_free_kbytes` | 44 MB | **256 MB** | kswapd's floor was 0.09% of a 48 GB VM |
| `vm.watermark_scale_factor` | 10 | **100** | Wake kswapd at 1% free, not 0.1%. Matters for MANY-AGENT bursts: when a dozen sessions allocate at once and background reclaim has not kept up, the allocating process enters DIRECT reclaim and stalls — felt as the box freezing for a moment, not as a memory shortage |

```bash
# absolute paths, like § F's block — these are run from any cwd, not only /opt/fabrik
/opt/fabrik/scripts/sysadmin/agent_memory.sh status             # knobs, swap, anon vs cache, Kilo
/opt/fabrik/scripts/sysadmin/agent_memory.sh install            # write + apply the sysctl file
/opt/fabrik/scripts/sysadmin/agent_memory.sh reclaim [--force]  # pull swapped pages back into RAM
/opt/fabrik/scripts/sysadmin/agent_memory.sh kilo on|off|status # Kilo Code on demand
/opt/fabrik/scripts/sysadmin/agent_memory.sh cron               # the daily entry point (see below)
```

**Why the policy lives in the script and not only in `/etc`.** So there is exactly ONE source of
truth: `/etc/sysctl.d/99-fabrik-agent-memory.conf` is GENERATED from the script, and the daily job
re-asserts it — healing a hand-edit, a package overwrite, or a file removed by someone tidying
`/etc/sysctl.d`, instead of silently reverting to swappiness 60. ⚠️ An earlier cut of this paragraph
justified it by claiming a `wsl --export`/`--import` rebuild wipes `/etc`. **That is false** —
[cleanup-maintenance-backlog.md](cleanup-maintenance-backlog.md) item A1 records that a full export
tar *"contains everything"*, and the only thing the rebuild resets is the default user. The design
stands; the reason given for it did not, and it was caught by a review seat opening the doc this
page had cited.

**`reclaim` is guarded, and the guard is the design.** `swapoff` must fit every swapped page back
into RAM at once and stalls the box for up to a minute. This tree routinely runs 3+ concurrent agent
sessions whose turns would freeze mid-tool-call, so it REFUSES while any `claude` process is alive,
and refuses again if the swapped bytes exceed `MemAvailable` (where `swapoff` would abort with
ENOMEM part-way) or if `/proc/meminfo` cannot be read at all. `--force` overrides. A refused `swapoff` that leaves the box unchanged returns **11** — distinct from the guard's own skip (**10**) and from a critical failure (**1**), because a box that never lost its swap must not break the heartbeat. The sysctl policy
prevents FUTURE bad eviction; only this undoes what is already out there.

⚠️ **`swapoff -a` and `swapon -a` are NOT symmetric, and on this box that difference is dangerous.**
`swapoff -a` takes down every device listed in `/proc/swaps`; `swapon -a` activates only devices
marked `swap` **in `/etc/fstab`** — and this box's fstab has **zero** swap entries. Swap here is
`/dev/sdc`, brought up by WSL init, with no systemd `.swap` unit either. So `swapon -a` restores
NOTHING and still exits 0, which means an exit-code check cannot detect it. `reclaim` therefore
captures the device list from `/proc/swaps` first, restores each **by name**, and verifies against
the kernel's own view rather than the return code. Found by a review seat 2026-09-20, before the
job had ever run unattended; the failure would have been a silent, swapless box until the next
`wsl --shutdown`, with the log reading `reclaimed.`

⚠️ **The daily job verifies the policy is IN EFFECT, not merely that it ran.** `sysctl -p` returns
0 even on an empty file, so re-asserting the policy proves nothing on its own. `cron` re-reads all
four live values and withholds the stamp when any disagrees — otherwise the heartbeat would measure
"the script was invoked" while the box ran on defaults (D-253, the cobra check: that was the
cheapest way to satisfy this measure without producing the outcome).

**Kilo Code runs on demand (operator directive 2026-09-20).** Its manifest declares
`"activationEvents": ["onStartupFinished", "onUri"]`, so it starts with EVERY window and there is no
lazy trigger to configure — enable/disable is the only lever, and `code --uninstall-extension` is
the only one the CLI can drive. Measured before removal: 8 processes, **2.29 GB**, several of them
in swap. ⚠️ Processes already spawned survive until each window is RELOADED.

**The cron line — ✅ INSTALLED 2026-09-20** (on the operator's explicit instruction; a crontab
write is otherwise classifier-blocked for an agent, and the 2026-08-19 wipe is why. It was appended
to a backup of the live crontab, never authored as a replacement: `~/backups/crontab.backup.*`,
120 → 125 lines, `comm` proving zero originals dropped). It rides `weekly_catchup.sh` rather than a
raw slot, so a missed night is caught up within the hour after the box wakes — plain cron has no
catch-up and this box hibernates:

```cron
11 * * * * flock -n $HOME/.claude/state/daily-agent-memory.lock /opt/fabrik/scripts/sysadmin/weekly_catchup.sh agent_memory.sh >> $HOME/.claude/agent-memory.log 2>&1
```

⚠️ **`PATH` is set inside the script, and that is load-bearing — but not for the reason it first
appears.** cron runs with `PATH=/usr/bin:/bin` and `sysctl`/`swapoff`/`swapon` live in `/usr/sbin`.
The **sudo'd** calls resolve anyway: `sudo -l` shows a `secure_path` covering `/usr/sbin`. What the
prepend actually rescues is the **unprivileged** `sysctl -n` in the status block, which printed four
EMPTY values under cron. Measured by running the job under `env -i PATH=/usr/bin:/bin` rather than
trusting an interactive shell, which cannot see this class at all; the "it would have died with
command not found" version of this paragraph was wrong and was corrected after a review seat read
`sudo -l` instead of assuming.

⚠️ **The exit code is the contract, and it has two halves.** **0** on success *or* on a benign
SKIP — a refused reclaim because sessions are live is the EXPECTED nightly outcome, and
`weekly_catchup.sh` stamps only on success, so returning non-zero there would re-run the job hourly
and flip `agent-memory-policy` to DEAD every night the operator is working. **1** on a CRITICAL
failure — a box left with no swap, or the policy not in effect — where the stamp is deliberately
withheld. So an overdue stamp means cron/the runner is broken **OR** the box lost its swap **OR**
the policy drifted; `~/.claude/agent-memory.log` distinguishes them.

**What this section deliberately does NOT do: drop caches on a schedule.** `echo 3 >
/proc/sys/vm/drop_caches` frees a headline number and buys nothing durable — the cache refills
within minutes of normal work, and it is what makes these file-dense trees fast. The 28 GB of
buff/cache was never the problem; the eviction ORDER was. A scheduled drop would be this page's
§ A design principle ("never forces needless re-downloads") violated in RAM.

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
